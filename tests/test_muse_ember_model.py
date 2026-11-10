"""Изолированные L1-тесты muse-ember-1.0: каталог, фасад, argv адаптера, MSP-поток, мост."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

import server
from adapters import ADAPTER_KINDS
from adapters.muse_adapter import MuseAdapter
from adapters.muse_msp import MspEvents
from core.fleet_compiler import compile_from_disk
from core.tool_emulation import StreamNormalizer

ROOT = Path(__file__).resolve().parents[1]
MODEL = "muse-ember-1.0"
TIERS = ("minimal", "low", "medium", "high", "xhigh", "max")


def _manifest() -> dict:
    return yaml.safe_load(
        (ROOT / "providers.d" / "muse.yaml").read_text(encoding="utf-8")
    )


def _entry() -> dict:
    return server.FLEET["models"][MODEL]


def test_manifest_declares_ember_and_family() -> None:
    manifest = _manifest()
    assert manifest["fingerprint"]["version"] == "1.4.15"
    assert manifest["fingerprint"]["binary_path"] == "~/.local/bin/muse"
    assert manifest["family_rule"]["exact_map"][MODEL] == "Meta"
    override = manifest["models_overrides"][MODEL]
    assert override["efforts"] == list(TIERS)
    assert override["default_effort"] == "high"
    assert override["context_window"] == 1048576
    assert override["max_tokens"] == 131072
    assert override["input"] == ["text"]
    assert override["policy_lines"] == [321]


def test_compiler_matches_fleet_and_sidecar_family() -> None:
    compiled = compile_from_disk(kinds=ADAPTER_KINDS)
    raw = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert compiled.fleet == raw
    record = next(m for m in raw["models"] if m["id"] == MODEL)
    assert record["max_tokens"] == 131072
    assert record["policy_lines"] == [321]
    assert record["images"]["cli_registry"] == "explicit_unsupported"
    assert compiled.sidecar["models"][MODEL]["family"] == "Meta"


def test_catalog_entry_and_models_card() -> None:
    entry = _entry()
    assert entry["backend"] == "muse"
    assert entry["efforts"] == list(TIERS)
    assert entry["default_effort"] == "high"
    assert entry["context_window"] == 1048576
    assert entry["input"] == ["text"]
    assert entry["images"]["status"] == "unsupported"
    assert server.FLEET["default_model"] == "muse-wonder-full-1.0"


def test_models_card_advertises_ember_efforts() -> None:
    card = next(c for c in server._build_models_list() if c["id"] == MODEL)
    assert card["owned_by"] == "meta-muse"
    assert card["context_window"] == 1048576
    assert card["context_length"] == 1048576
    # Кэп max_output_tokens в хабе общий (BRIDGE_MAX_OUTPUT_TOKENS), не из записи модели.
    assert card["max_output_tokens"] == server.MAX_OUTPUT_TOKENS
    fields = server.resolve_model_effort_fields(MODEL, server._effort_specs())
    assert fields is not None
    assert tuple(fields.supported_efforts) == TIERS
    assert fields.default_effort == "high"


def test_effort_resolution_for_all_tiers() -> None:
    entry = _entry()
    allowed, default = entry["efforts"], entry["default_effort"]
    for tier in TIERS:
        assert server.clamp_effort_downward(tier, allowed, default) == (tier, False)
    assert server.clamp_effort_downward("off", allowed, default) == ("minimal", True)
    assert server.clamp_effort_downward("ultra", allowed, default) == ("max", True)
    assert server.clamp_effort_downward("bogus", allowed, default) == ("high", True)
    assert server.clamp_effort_downward("", allowed, default) == ("high", True)


def _adapter() -> MuseAdapter:
    config = {"max_concurrent": 1, "wrapper": "/tmp/muse", "options": {"streaming_mode": "exec"}}
    return MuseAdapter("muse", config, lambda: server.FLEET)


@pytest.mark.parametrize("tier", TIERS)
def test_build_argv_carries_every_tier(tier: str) -> None:
    argv = _adapter().build_argv(MODEL, tier, "/tmp/p.txt")
    assert argv[:8] == [
        "/tmp/muse",
        "exec",
        "--provider",
        "meta",
        "--model",
        MODEL,
        "--reasoning-effort",
        tier,
    ]
    assert "--yolo" in argv and "--trust-workspace" in argv and "--json" in argv
    assert argv[-2:] == ["--prompt-file", "/tmp/p.txt"]
    assert "--disable-write" not in argv and "--disable-shell" not in argv


def test_msp_steps_separated_and_tool_markers_sanitized() -> None:
    events = MspEvents(reasoning_cap=10_000, answer_cap=10_000)
    events.feed("item/started", {"item": {"itemId": "r1", "kind": "reasoning"}})
    first = events.feed(
        "item/delta",
        {"itemId": "r1", "kind": "reasoning", "field": "summary.0", "delta": "Первый шаг."},
    )
    second = events.feed(
        "item/delta",
        {"itemId": "r1", "kind": "reasoning", "field": "summary.1", "delta": "Второй шаг."},
    )
    assert first == "Первый шаг."
    assert second == "\n\nВторой шаг."
    assert "Первый шаг.\n\nВторой шаг." in events.reasoning
    assert "шаг.Второй" not in events.reasoning
    started = events.feed(
        "item/started", {"item": {"itemId": "t1", "kind": "toolCall", "toolName": "Bash"}}
    )
    assert started == "[Вызов инструмента: Bash]\n"
    events.feed(
        "item/started", {"item": {"itemId": "t2", "kind": "toolCall", "toolName": "bad name\nx"}}
    )
    assert events.reasoning.endswith("[Вызов инструмента: unknown_tool]\n")
    assert events.has_executed_tool is True


def test_tool_call_block_extracted_from_stream() -> None:
    calls: list[dict] = []
    content: list[str] = []
    normalizer = StreamNormalizer(on_content=content.append, on_tool_call=calls.append)
    normalizer.feed('До. <tool_call>{"name": "Bash", "arguments": {"cmd": "ls"}}</tool_call> После.')
    normalizer.finish()
    assert len(calls) == 1
    assert calls[0]["name"] == "Bash"
    assert calls[0]["arguments"] == {"cmd": "ls"}
    assert "<tool_call>" not in "".join(content)


def _bridge_module() -> object:
    path = ROOT / "bridges" / "muse-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location("muse_bridge_ember_l1", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_muse_bridge_allowed_models_and_effort_map() -> None:
    bridge = _bridge_module()
    assert bridge.ALLOWED_MODELS[MODEL] == {"context_length": 400_000, "max_output": 131072}
    assert bridge._context_limit(MODEL) == 400_000
    assert bridge._context_target(400_000) == 320_000
    assert bridge._context_retry_target(400_000) == 200_000
    expected = {
        "minimal": "minimal",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "xhigh",
        "max": "max",
        "off": "minimal",
        "none": "minimal",
        "ultra": "xhigh",
    }
    for raw, tier in expected.items():
        assert bridge._map_effort({"reasoning_effort": raw}) == tier
    assert bridge._MSP_EFFORT["minimal"] == "low"
    assert bridge._MSP_EFFORT["max"] == "max"


def test_hub_adapter_runs_ember_through_serve_msp() -> None:
    """Прод-транспорт провайдера muse — `serve` (MSP), не `exec`: ход идёт в нативный стрим."""
    config = {"max_concurrent": 1, "wrapper": "/tmp/muse", "options": {"streaming_mode": "serve"}}
    adapter = MuseAdapter("muse", config, lambda: server.FLEET)
    assert adapter.streaming_mode == "serve"
    assert adapter.capabilities.streaming == "native"
    assert _entry()["backend"] == "muse"


def test_muse_bridge_reexports_shared_tool_call_parser() -> None:
    """F-001: паритетный тест грузит мост второй реализацией и зовёт `_parse_tool_call_blocks`."""
    bridge = _bridge_module()
    assert "_parse_tool_call_blocks" in bridge.__all__
    assert bridge._parse_tool_call_blocks('{"name":"a","arguments":{"x":1}}}') == [
        {"name": "a", "arguments": {"x": 1}}
    ]
    assert bridge._parse_tool_call_blocks('{"name":"a","arguments":{}}, "x": 1}') is None


def test_bridge_serve_payload_maps_ember_effort_to_msp() -> None:
    """F-003: `turn/start.reasoningEffort` = `_MSP_EFFORT[_map_effort(tier)]`, не молчаливый `max`."""
    bridge = _bridge_module()
    mapped = {
        tier: bridge._MSP_EFFORT[bridge._map_effort({"reasoning_effort": tier})]
        for tier in TIERS
    }
    assert mapped == {
        "minimal": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "xhigh",
        "max": "max",
    }
    assert mapped["xhigh"] == bridge._MSP_EFFORT[bridge._map_effort({"reasoning_effort": "ultra"})]


class _PatchLoader(yaml.SafeLoader):
    """DSH-патч содержит встроенный JS (`!!js process.platform ...`) — читаем его как строку."""


_PatchLoader.add_constructor(
    "tag:yaml.org,2002:js", lambda loader, node: loader.construct_scalar(node)
)

DSH_PROFILES = tuple(
    Path.home() / ".dsh" / "profiles" / name / "cordis.patch.yml"
    for name in ("desktop", "web")
)
DSH_FIXTURE = """
- id: llm-pi-ai
  config:
    providers:
      muse-bridge:
        displayName: Meta Muse Bridge (:9882)
        baseURL: http://127.0.0.1:9882/v1
        models:
          - id: muse-ember-1.0
            name: Muse Ember 1.0 (Muse)
            contextWindow: 400000
            maxTokens: 131072
            input: [text]
            reasoningEfforts: {off: null, minimal: minimal, low: low, medium: medium, high: high, xhigh: xhigh, max: max}
- id: subagent-model-selection-settings
  config:
    allowedModels:
      - provider: muse-bridge
        model: muse-ember-1.0
"""


def _assert_dsh_ember(patch: str) -> None:
    """Контракт DSH-патча: окно 400k, text-only, живой `xhigh`, модель в пикере сабагентов."""
    # Патч содержит и `- insert:`-правки без `id` — в карту секций идут только именованные.
    sections = {
        item["id"]: item
        for item in yaml.load(patch, Loader=_PatchLoader)
        if isinstance(item, dict) and "id" in item
    }
    provider = sections["llm-pi-ai"]["config"]["providers"]["muse-bridge"]
    assert provider["baseURL"].endswith(":9882/v1")
    entry = next(m for m in provider["models"] if m["id"] == MODEL)
    assert entry["contextWindow"] == 400_000
    assert entry["maxTokens"] == 131072
    assert entry["input"] == ["text"]
    # Ключ `off` PyYAML (YAML 1.1) читает как boolean, поэтому отключение проверяем по значению.
    efforts = entry["reasoningEfforts"]
    assert {k: v for k, v in efforts.items() if isinstance(k, str)} == {
        "minimal": "minimal",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "xhigh",
        "max": "max",
    }
    assert None in efforts.values()
    allowed = sections["subagent-model-selection-settings"]["config"]["allowedModels"]
    assert {"provider": "muse-bridge", "model": MODEL} in allowed


def test_dsh_patch_contract_for_ember() -> None:
    """F-006: встроенная фикстура проверяется всегда, реальные профили DSH — если они есть."""
    _assert_dsh_ember(DSH_FIXTURE)
    for path in DSH_PROFILES:
        if path.exists():
            _assert_dsh_ember(path.read_text(encoding="utf-8"))
