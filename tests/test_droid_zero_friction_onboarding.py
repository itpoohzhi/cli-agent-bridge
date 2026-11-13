from __future__ import annotations

# Zero-Friction онбординг Factory Droid: манифесты, приоритеты, алиасы, `fleet_compile --explain`.

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters import ADAPTER_KINDS  # noqa: E402
from core.backend_adapter import build_catalog  # noqa: E402
from core.fleet_compiler import compile_from_disk, load_header  # noqa: E402
from core.model_resolver import resolve_model  # noqa: E402
from core.provider_manifest import load_manifests  # noqa: E402
from tools import fleet_compile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ROOT / "providers.d"
NOW = "2026-11-07T00:00:00+03:00"
LMH = ["low", "medium", "high"]
DROID_MODELS = {  # model_id -> (вендор, default_effort, efforts)
    "gpt-6.1-sol": ("OpenAI", "high", LMH),
    "claude-sonnet-5-5": ("Anthropic", "high", [*LMH, "max"]),
    "gemini-3.8-flash": ("Google", "high", LMH),
    "gpt-6.1-sol-droid": ("OpenAI", "high", [*LMH, "max"]),
    "claude-sonnet-5-5-droid": ("Anthropic", "high", [*LMH, "max"]),
    "gemini-3.8-flash-droid": ("Google", "high", LMH),
}
PRIMARY = {
    "gpt-6.1-sol": "codex",
    "claude-sonnet-5-5": "claude-p",
    "gemini-3.8-flash": "agy",
    "gpt-6.1-sol-droid": "droid",
    "claude-sonnet-5-5-droid": "droid",
    "gemini-3.8-flash-droid": "droid",
    "claude-opus-5-5": "claude-p",
    "claude-haiku-5-5": "opencode-go-claude",
    "gemini-4-argon": "agy",
    "gemini-4-carbon": "agy",
    "gpt-6.1-terra": "codex",
}
ALTERNATES = {
    "gpt-6.1-sol": ["droid"],
    "claude-sonnet-5-5": ["droid"],
    "gemini-3.8-flash": ["droid"],
    "claude-haiku-5-5": ["claude-p"],
}
GO_ONLY = ("deepseek-v4.1-flash",)  # вне droid: только мост opencode-go; kimi-k3.1-pro удалена из каталога
SUFFIX_ALIASES = {
    **{
        f"gemini-3.8-flash-droid-{effort}": {
            "backend_id": "gemini-3.8-flash-droid",
            "backend": "droid",
            "effort": effort,
        }
        for effort in LMH
    },
    **{
        f"gpt-6.1-sol-droid-{effort}": {
            "backend_id": "gpt-6.1-sol-droid",
            "backend": "droid",
            "effort": effort,
        }
        for effort in (*LMH, "max")
    },
    **{
        f"claude-sonnet-5-5-droid-{effort}": {
            "backend_id": "claude-sonnet-5-5-droid",
            "backend": "droid",
            "effort": effort,
        }
        for effort in (*LMH, "max")
    },
    **{
        f"gpt-6.1-sol-{effort}": {
            "backend_id": "gpt-6.1-sol",
            "backend": "codex",
            "effort": effort,
        }
        for effort in (*LMH, "max")
    },
    **{
        f"gemini-4-carbon-{effort}": {
            "target": "gemini-4-carbon",
            "default_effort": effort,
        }
        for effort in LMH
    },
    "gemini-4-argon-low": {
        "target": "gemini-4-argon",
        "default_effort": "low",
    },
    "gemini-4-argon-medium": {
        "target": "gemini-4-argon",
        "default_effort": "medium",
    },
    "gemini-4-argon-high": {
        "backend_id": "gemini-4-argon",
        "backend": "agy",
        "effort": "high",
    },
    **{
        f"gemini-3.8-flash-{effort}": {
            "backend_id": "gemini-3.8-flash",
            "backend": "agy",
            "effort": effort,
        }
        for effort in LMH
    },
    **{
        f"claude-sonnet-5-5-{effort}": {
            "backend_id": "claude-sonnet-5-5",
            "backend": "claude-p",
            "effort": effort,
        }
        for effort in (*LMH, "max")
    },
    **{
        f"claude-opus-5-5-{effort}": {
            "backend_id": "claude-opus-5-5",
            "backend": "claude-p",
            "effort": effort,
        }
        for effort in ("medium", "high")
    },
    "claude-haiku-5-5-low": {
        "backend_id": "claude-haiku-5-5",
        "backend": "opencode-go-claude",
        "effort": "low",
    },
}


@pytest.fixture(scope="module")
def compiled() -> Any:
    return compile_from_disk(kinds=ADAPTER_KINDS, now=NOW)


def _aliases() -> dict[str, Any]:
    return dict(load_header(PROVIDERS / "_fleet.yaml")["aliases"])


# ---- манифесты и тай-брейк ------------------------------------------------------------


def test_droid_manifest_registers_three_subscription_models() -> None:
    droid = next(
        m
        for m in load_manifests(PROVIDERS, ADAPTER_KINDS).manifests
        if m.provider_id == "droid"
    )
    assert (droid.enabled, droid.priority) == (True, 30)
    limits = droid.limits
    assert (limits.max_concurrent, limits.quota_group, limits.timeout_s) == (
        32,
        "factory-droid",
        450,
    )
    assert {r.model_id for r in droid.models_overrides} == set(DROID_MODELS)
    for rule in droid.models_overrides:
        vendor, default, efforts = DROID_MODELS[rule.model_id]
        assert rule.fields["efforts_pin"] == efforts  # ladder пробника ограничен
        assert rule.fields["efforts"] == efforts
        assert rule.fields["default_effort"] == default
        assert droid.family_rule.exact_map[rule.model_id] == vendor


def test_provider_priorities() -> None:
    manifests = load_manifests(PROVIDERS, ADAPTER_KINDS).manifests
    expected = {
        "droid": 30,
        "claude-p": 10,
        "agy": 10,
        "muse": 10,
        "codex": 10,
        "opencode-go": 10,
        "opencode-go-claude": 5,
        "opencode-zen": 50,
    }
    assert {m.provider_id: m.priority for m in manifests} == expected


def test_primary_and_alternates_follow_priority(compiled: Any) -> None:
    backends = {m["id"]: m["backend"] for m in compiled.fleet["models"]}
    for mid, provider in PRIMARY.items():
        assert compiled.sidecar["models"][mid]["provider"] == provider
        assert backends[mid] == provider
    for mid, alternates in ALTERNATES.items():
        assert [
            a["provider"] for a in compiled.sidecar["models"][mid]["alternates"]
        ] == alternates
    for mid in GO_ONLY:
        assert compiled.sidecar["models"][mid]["provider"] == "opencode-go"
        assert backends[mid] == "opencode-go"
        assert compiled.sidecar["models"][mid]["alternates"] == []
    assert "kimi-k3.1-pro" not in compiled.sidecar["models"]
    assert compiled.rejected == {} and compiled.rejected_providers == {}


def test_claude_p_efforts_are_extended(compiled: Any) -> None:
    by_id = {m["id"]: m for m in compiled.fleet["models"]}
    for mid, default in (("claude-opus-5-5", "high"), ("claude-haiku-5-5", "low")):
        assert by_id[mid]["efforts"] == LMH and by_id[mid]["default_effort"] == default


def test_fleet_json_is_in_sync(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    assert fleet_compile.main(["--check"]) == 0
    raw = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    droid = raw["backends"]["droid"]
    assert droid["enabled"] is True and droid["max_concurrent"] == 32
    # Версия/пин бинаря — из шапки манифеста, а не литерал теста (пере-снятие провенанса).
    header = load_header(PROVIDERS / "_fleet.yaml")
    assert raw["technical_ref"] == header["technical_ref"]


def test_explain_prints_deterministic_tiebreak(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    outputs: list[str] = []
    for _ in range(2):
        assert fleet_compile.main(["--explain", "gpt-6.1-sol"]) == 0
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]
    doc = json.loads(outputs[0])
    assert (doc["model_id"], doc["primary"], doc["alternates"]) == (
        "gpt-6.1-sol",
        "codex",
        ["droid"],
    )
    assert [(c["priority"], c["provider_id"]) for c in doc["candidates"]] == [
        (10, "codex"),
        (30, "droid"),
    ]


def test_explain_unknown_model_fails(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    assert fleet_compile.main(["--explain", "no-such-model"]) == 1
    assert capsys.readouterr().out == ""


# ---- алиасы ---------------------------------------------------------------------------


def test_suffix_aliases_match_pinned_ids_and_catalog(compiled: Any) -> None:
    aliases = _aliases()
    assert "deepseek-v4.1-flash" not in aliases
    assert aliases == SUFFIX_ALIASES
    by_id = {m["id"]: m for m in compiled.fleet["models"]}
    for entry in aliases.values():
        model = by_id[entry.get("backend_id", entry.get("target"))]
        if "backend" in entry:
            assert model["backend"] == entry["backend"]
        assert entry.get("effort", entry.get("default_effort")) in model["efforts"]


@pytest.mark.parametrize(
    "alias",
    ["gpt-6.1-sol-high", "gemini-3.8-flash-medium", "claude-haiku-5-5-low"],
)
def test_suffix_alias_resolves_to_base_with_effort(compiled: Any, alias: str) -> None:
    models = build_catalog(compiled.fleet, ADAPTER_KINDS)["models"]
    entry = SUFFIX_ALIASES[alias]
    base = entry.get("backend_id", entry.get("target"))
    effort = entry.get("effort", entry.get("default_effort"))
    resolved = resolve_model(alias, models, _aliases())
    assert (resolved.base_id, resolved.effort) == (base, effort)


def test_deepseek_flash_is_not_redirected_to_free(compiled: Any) -> None:
    models = build_catalog(compiled.fleet, ADAPTER_KINDS)["models"]
    assert models["deepseek-v4.1-flash"]["backend"] == "opencode-go"  # не droid
    assert "deepseek-v4.1-flash" not in _aliases()
    assert (
        "deepseek-v4.1-flash-free" in models
    )  # явный бесплатный ID остаётся доступным
