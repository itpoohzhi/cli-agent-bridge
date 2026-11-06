"""Подписочные модели Droid: каталог, fail-closed tools-policy и изолированные пробы."""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

import pytest

import server
from tools import droid_image

DROID_MODEL_IDS = (
    "claude-sonnet-5-5",
    "gemini-3.8-flash",
    "deepseek-v4.1-flash",
    "gpt-6.1-sol",
    "kimi-k3.1-pro",
)
BASE_TOOLS = tuple(f"tool-{index}" for index in range(35))
EXTRA_TOOL = "wait-for-script-cli"
MODEL_EFFORTS = (
    ("low", "medium", "high", "max"),
    ("low", "medium", "high"),
    ("off", "low", "medium", "high"),
    ("low", "medium", "high"),
    ("low", "medium", "high"),
)


def fleet_data() -> dict:
    return json.loads((Path(server.ROOT) / "fleet.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("model_id", "efforts"), tuple(zip(DROID_MODEL_IDS, MODEL_EFFORTS))
)
def test_subscription_catalog(model_id: str, efforts: tuple[str, ...]) -> None:
    catalog = server._build_catalog(fleet_data())
    model = catalog["models"][model_id]
    assert model["backend"] == "droid"
    assert model["efforts"] == list(efforts)
    assert model["default_effort"] == (
        "off" if model_id == "deepseek-v4.1-flash" else "high"
    )
    assert model["name"].endswith("(Droid bridge)")
    assert server.BACKENDS.adapter_for_model(model_id).id == "droid"


def test_kimi_limits_and_unverified_images() -> None:
    model = next(m for m in fleet_data()["models"] if m["id"] == "kimi-k3.1-pro")
    assert (model["context_window"], model["max_tokens"]) == (262144, 16384)
    assert model["input"] == ["text"]
    assert model["images"] == {
        "cli_registry": "implicit_supported",
        "status": "unverified",
        "method": None,
        "proof": None,
    }


@pytest.mark.parametrize("model_id", ("kimi-k3.1-pro", "deepseek-v4.1-flash"))
def test_exact_catalog_ids_beat_effort_alias(
    monkeypatch: pytest.MonkeyPatch, model_id: str
) -> None:
    monkeypatch.setattr(server, "EFFORT_ALIAS_ENABLED", True)
    catalog = server._build_catalog(fleet_data())["models"]
    assert server._resolve_model_alias(model_id, catalog) is None
    assert server._resolve_model_alias(model_id + "-high", catalog) == (
        model_id,
        "high",
    )
    catalog[model_id + "-high"] = catalog[model_id]
    assert server._resolve_model_alias(model_id + "-high", catalog) is None


def test_deepseek_off_is_validated_by_shared_catalog() -> None:
    catalog = server._build_catalog(fleet_data())
    assert "off" in server.EFFORT_LEVELS
    assert catalog["aliases"] == {}
    assert "off" in catalog["models"]["deepseek-v4.1-flash"]["efforts"]


@pytest.fixture
def qualified_tools(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    tools = list(BASE_TOOLS)
    qualified = {mid: list(tools) for mid in DROID_MODEL_IDS}
    monkeypatch.setattr(server, "RECEIPT_REQUIRED", True)
    monkeypatch.setattr(
        server,
        "_load_receipt",
        lambda: (
            None,
            {
                "tools_policy": {"disabled_tool_ids": tools},
                "qualified_models": qualified,
            },
        ),
    )
    return tools


@pytest.mark.parametrize("model", DROID_MODEL_IDS)
def test_exact_qualified_tools_pass(qualified_tools: list[str], model: str) -> None:
    run = object.__new__(server.Run)
    run.plan = {"settings": (model, "high", "high")}
    run._check_tools_policy(qualified_tools)


@pytest.mark.parametrize(
    "listed", ([], ["evil-tool"], [*BASE_TOOLS, "evil-tool"], list(BASE_TOOLS[:-1]))
)
def test_empty_or_unqualified_tools_are_blocked(
    qualified_tools: list[str], listed: list[str]
) -> None:
    run = object.__new__(server.Run)
    run.plan = {"settings": (DROID_MODEL_IDS[0], "high", "high")}
    with pytest.raises(server.RpcError, match="qualified tools policy"):
        run._check_tools_policy(listed)


@pytest.mark.parametrize("model", DROID_MODEL_IDS)
def test_missing_model_qualification_is_blocked(
    qualified_tools: list[str], model: str
) -> None:
    _, receipt = server._load_receipt()
    del receipt["qualified_models"][model]
    run = object.__new__(server.Run)
    run.plan = {"settings": (model, "high", "high")}
    with pytest.raises(server.RpcError, match="qualified tools policy"):
        run._check_tools_policy(qualified_tools)


class FakeRpc:
    """Только синхронные данные, никаких процессов, сокетов и ожиданий."""

    instances: list[FakeRpc] = []
    invalid_model = ""
    omit_disabled = False
    protocol = "test-protocol"

    def __init__(self, image: Path, cwd: Path, home: Path) -> None:
        self.settings: dict = {}
        self.calls: list[tuple[str, dict]] = []
        self.closed = False
        self.instances.append(self)

    def call(self, method: str, params: dict) -> tuple[dict, list]:
        self.calls.append((method, params))
        if method == "droid.initialize_session":
            self.settings = dict(params)
            return {"sessionId": "fake-sid", "settings": dict(params)}, []
        if method == "droid.list_tools":
            if self.settings["modelId"] == self.invalid_model:
                return {"tools": []}, []
            ids = [*BASE_TOOLS]
            if self.settings["modelId"] == "gpt-6.1-sol":
                ids.append(EXTRA_TOOL)
            return {"tools": [{"id": tool} for tool in ids]}, []
        if method == "droid.update_session_settings":
            self.settings.update(params)
            updated = dict(self.settings)
            if self.omit_disabled:
                updated["disabledToolIds"] = []
            return {}, [
                {"notification": {"type": "settings_updated", "settings": updated}}
            ]
        if method == "droid.load_session":
            return {"session": {"messages": []}, "settings": dict(self.settings)}, []
        raise AssertionError(method)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_probes(monkeypatch: pytest.MonkeyPatch) -> type[FakeRpc]:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("В L1 запрещены процессы, сокеты и sleep")

    monkeypatch.setattr(FakeRpc, "instances", [])
    monkeypatch.setattr(droid_image, "_Rpc", FakeRpc)
    monkeypatch.setattr(droid_image.subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(droid_image.time, "sleep", forbidden)
    return FakeRpc


def started_models(rpc_type: type[FakeRpc]) -> list[str]:
    return [
        params["modelId"]
        for rpc in rpc_type.instances
        for method, params in rpc.calls
        if method == "droid.initialize_session"
    ]


def test_probes_union_all_model_tools(
    monkeypatch: pytest.MonkeyPatch, fake_probes: type[FakeRpc], tmp_path: Path
) -> None:
    monkeypatch.delenv("DROID_EXTRA_PROBE_MODELS", raising=False)
    facts = droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert facts["disabled_tool_ids"] == sorted([*BASE_TOOLS, EXTRA_TOOL])
    assert started_models(fake_probes) == list(DROID_MODEL_IDS)
    assert set(facts["qualified_models"]) == set(DROID_MODEL_IDS)
    assert facts["qualified_models"]["gpt-6.1-sol"] == sorted([*BASE_TOOLS, EXTRA_TOOL])
    initializes = [
        params
        for rpc in fake_probes.instances
        for method, params in rpc.calls
        if method == "droid.initialize_session"
    ]
    assert (
        next(
            p["reasoningEffort"]
            for p in initializes
            if p["modelId"] == "deepseek-v4.1-flash"
        )
        == "off"
    )
    assert facts["protocol_version"] == "test-protocol"
    assert facts["probes"] == {"spawn": "ok", "update": "ok", "load": "ok"}
    assert all(rpc.closed for rpc in fake_probes.instances)
    updates = [
        params["disabledToolIds"]
        for rpc in fake_probes.instances
        for method, params in rpc.calls
        if method == "droid.update_session_settings"
    ]
    assert updates == [
        sorted([*BASE_TOOLS, EXTRA_TOOL] if mid == "gpt-6.1-sol" else BASE_TOOLS)
        for mid in DROID_MODEL_IDS
    ]


@pytest.mark.parametrize(
    ("extra_models", "expected"),
    [
        ("", []),
        ("kimi-k3.1-pro, kimi-k3.1-pro,,claude-sonnet-5-5", []),
        ("future-model:low", ["future-model"]),
    ],
)
def test_configured_probe_models_are_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
    fake_probes: type[FakeRpc],
    extra_models: str,
    expected: list[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", extra_models)
    facts = droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert started_models(fake_probes) == [*DROID_MODEL_IDS, *expected]
    assert facts["disabled_tool_ids"] == sorted([*BASE_TOOLS, EXTRA_TOOL])
    assert all(rpc.closed for rpc in fake_probes.instances)


def test_bad_extra_probe_fails_closed(
    monkeypatch: pytest.MonkeyPatch, fake_probes: type[FakeRpc], tmp_path: Path
) -> None:
    monkeypatch.setenv("DROID_EXTRA_PROBE_MODELS", "gpt-6.1-sol")
    monkeypatch.setattr(fake_probes, "invalid_model", "gpt-6.1-sol")
    with pytest.raises(droid_image.ProbeError, match="list_tools"):
        droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert all(rpc.closed for rpc in fake_probes.instances)


def test_tools_must_be_confirmed_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_probes: type[FakeRpc], tmp_path: Path
) -> None:
    monkeypatch.setattr(fake_probes, "omit_disabled", True)
    with pytest.raises(droid_image.ProbeError, match="отключение tools"):
        droid_image.run_probes(Path("/fake/droid"), tmp_path)
    assert all(rpc.closed for rpc in fake_probes.instances)


def test_probe_timeout_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROID_PROBE_TIMEOUT_S", "2.75")
    spec = importlib.util.spec_from_file_location(
        "probe_timeout_test", droid_image.__file__
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._get_probe_timeout_s() == 2.75
