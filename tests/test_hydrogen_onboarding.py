"""Онбординг `gemini-4-hydrogen` (Google, AGY): каталоги, модальности хаба, effort-лестница моста."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

MODEL = "gemini-4-hydrogen"
EFFORTS = ["low", "medium", "high", "xhigh"]
ALIASES = tuple(f"{MODEL}-{effort}" for effort in EFFORTS)
SIBLINGS = ("gemini-4-carbon", "gemini-4-argon", "gemini-3.8-flash")
SIBLING_EFFORTS = ["low", "medium", "high"]
AGY_BINARY_SHA256 = "e872cc54b5381f401c798fc947937a0a930876b849bc3fee654996ba4ab236a8"
_BRIDGE_PY = ROOT / "bridges" / "agy-bridge" / "server.py"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _model(doc: dict[str, Any], model_id: str) -> dict[str, Any]:
    models = doc["models"]
    if isinstance(models, dict):
        return models[model_id]
    return next(item for item in models if item["id"] == model_id)


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-hydrogen-onboarding")
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_hydrogen_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---- корневой каталог хаба: fleet.json + catalog.lock.json ------------------------


def test_root_fleet_registers_hydrogen_under_agy() -> None:
    fleet = _load_json(ROOT / "fleet.json")
    entry = _model(fleet, MODEL)
    assert entry["backend"] == "agy"
    assert entry["efforts"] == EFFORTS
    assert entry["default_effort"] == "high"
    assert entry["context_window"] == 1048576
    assert entry["max_tokens"] == 65536
    for effort in EFFORTS:
        alias = fleet["aliases"][f"{MODEL}-{effort}"]
        assert alias == {"target": MODEL, "default_effort": effort}


def test_root_catalog_lock_registers_hydrogen_under_agy() -> None:
    lock = _load_json(ROOT / "catalog.lock.json")
    entry = _model(lock, MODEL)
    assert entry["provider"] == "agy"
    assert entry["in_fleet"] is True
    assert entry["family"] == "Google"
    assert entry["quota_group"] == "google-agy"


def test_root_catalog_lock_matches_fleet_digest() -> None:
    """Сайдкар фиксирует sha256 именно того fleet.json, что лежит в корне."""
    import hashlib

    from core.fleet_compiler import render_fleet_json

    fleet = _load_json(ROOT / "fleet.json")
    lock = _load_json(ROOT / "catalog.lock.json")
    digest = hashlib.sha256(render_fleet_json(fleet)).hexdigest()
    assert lock["fleet_sha256"] == digest


# ---- модальности в `/v1/models` хаба ---------------------------------------------


def test_hub_modalities_include_image_for_hydrogen_and_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", ALIASES)
    monkeypatch.setattr(server, "_EFFORT_SPECS_CACHE", (None, {}))
    cards = {card["id"]: card for card in server._build_models_list()}
    assert MODEL in cards and set(ALIASES) <= set(cards)
    for model_id in (MODEL, *ALIASES):
        assert cards[model_id]["modalities"] == ["text", "image"], model_id


def test_model_modalities_helper_contract() -> None:
    assert server._model_modalities({}, MODEL) == ["text", "image"]
    assert server._model_modalities({"input": ["text", "image"]}, "x-model") == [
        "text",
        "image",
    ]
    assert server._model_modalities({"input": ["text"]}, "gemini-4-carbon") == ["text"]


# ---- мост AGY: fleet.json и effort-лестница --------------------------------------


def test_agy_bridge_fleet_registers_hydrogen_with_confirmed_images() -> None:
    fleet = _load_json(ROOT / "bridges" / "agy-bridge" / "fleet.json")
    entry = _model(fleet, MODEL)
    assert entry["efforts"] == EFFORTS
    assert entry["default_effort"] == "high"
    assert entry["context_window"] == 1048576
    assert entry["max_tokens"] == 65536
    assert entry["input"] == ["text", "image"]
    images = entry["images"]
    assert images["status"] == "confirmed"
    assert images["method"] == "workspace-read"
    proof = images["proof"]
    assert proof["agy_binary_sha256"] == AGY_BINARY_SHA256
    assert proof["impl_version"] == 1
    assert proof["efforts_proven"] == EFFORTS
    assert "image/png" in proof["formats"]


def test_agy_bridge_siblings_keep_three_level_ladder() -> None:
    fleet = _load_json(ROOT / "bridges" / "agy-bridge" / "fleet.json")
    for model_id in SIBLINGS:
        assert _model(fleet, model_id)["efforts"] == SIBLING_EFFORTS, model_id


@pytest.fixture(scope="module")
def bridge_module() -> Any:
    return _load_bridge()


def test_agy_bridge_cli_effort_levels_include_xhigh(bridge_module: Any) -> None:
    assert "xhigh" in bridge_module.CLI_EFFORT_LEVELS
    assert set(SIBLING_EFFORTS) <= set(bridge_module.CLI_EFFORT_LEVELS)
    for model_id in (MODEL, *SIBLINGS):
        assert model_id in bridge_module.FLEET["models"], model_id
    assert bridge_module.FLEET["models"][MODEL]["efforts"] == EFFORTS
    for model_id in SIBLINGS:
        assert bridge_module.FLEET["models"][model_id]["efforts"] == SIBLING_EFFORTS


class _Http:
    """Настоящий HTTP-сервер моста на свободном порту (agy не запускается: отказ до спавна)."""

    def __init__(self, module: Any) -> None:
        self.module = module
        self.server = module.Server(("127.0.0.1", 0), module.Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(10)

    def post(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + str(self.module.AUTH_KEY),
        }
        conn.request("POST", "/v1/chat/completions", json.dumps(body), headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw.decode("utf-8"))


def _body(model: str, effort: str) -> dict[str, Any]:
    # `reasoning` отвергается СРАЗУ ПОСЛЕ проверки effort: так принятие xhigh видно как
    # `unsupported_parameter`, а отказ — как `unsupported_reasoning_effort`, без спавна agy.
    return {
        "model": model,
        "messages": [{"role": "user", "content": "PONG"}],
        "reasoning_effort": effort,
        "reasoning": {"effort": effort},
    }


def test_per_model_effort_check_rejects_xhigh_on_siblings_only(
    bridge_module: Any,
) -> None:
    http_bridge = _Http(bridge_module)
    try:
        for model_id in SIBLINGS:
            code, payload = http_bridge.post(_body(model_id, "xhigh"))
            assert code == 400, model_id
            assert payload["error"]["type"] == "unsupported_reasoning_effort", model_id
        code, payload = http_bridge.post(_body(MODEL, "xhigh"))
        assert code == 400
        assert payload["error"]["type"] == "unsupported_parameter"
        code, payload = http_bridge.post(_body(MODEL, "max"))
        assert code == 400
        assert payload["error"]["type"] == "unsupported_reasoning_effort"
    finally:
        http_bridge.close()
