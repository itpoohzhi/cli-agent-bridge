from __future__ import annotations

# Effort на границе роутинга: шкала, кламп passthrough, честный `/v1/models`, инварианты гейта.

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core import backend_adapter  # noqa: E402
from core import effort_policy  # noqa: E402
from core import quarantine_gate as qg  # noqa: E402
from core.effort_policy import (  # noqa: E402
    DEFAULT_LOG_EFFORT_MAX_CHARS,
    ModelEffortSpec,
    clamp_effort_downward,
    describe_clamp,
    resolve_passthrough_effort,
    sanitize_effort_for_log,
)

route = importlib.import_module("test_passthrough_routing").route  # фикстура do_POST без сети
LMH = ["low", "medium", "high"]
SPEC = ModelEffortSpec(tuple(LMH), "high")


# ---- effort: шкала, кламп, passthrough -------------------------------------------------


def test_catalog_effort_levels_extend_policy_scale_with_off() -> None:
    ranked = effort_policy.EFFORT_LEVELS
    assert ranked == ("minimal", "low", "medium", "high", "xhigh", "max")
    assert backend_adapter.EFFORT_LEVELS == ("off", *ranked)
    assert backend_adapter.EFFORT_LEVELS is server.EFFORT_LEVELS
    assert effort_policy.EFFORT_ORDER == ("off", *ranked, "ultra")


def test_clamp_off_maps_to_lowest_allowed() -> None:
    assert server.clamp_effort_downward is clamp_effort_downward
    assert clamp_effort_downward("off", LMH, "high") == ("low", True)
    assert clamp_effort_downward("max", LMH, "high") == ("high", True)
    assert clamp_effort_downward("off", ["high"], "high") == ("high", True)


def test_passthrough_stays_transparent_without_effort() -> None:
    decision = resolve_passthrough_effort(None, None, SPEC, enabled=True)
    assert (decision.apply, decision.value) == (False, None)


@pytest.mark.parametrize(
    "requested,allowed,value",
    [
        ("off", LMH, "low"),
        ("max", LMH, "high"),
        ("max", ["high"], "high"),
        ("xhigh", LMH, "high"),
    ],
)
def test_passthrough_clamps_unsupported_effort(
    requested: str, allowed: list[str], value: str
) -> None:
    spec = ModelEffortSpec(tuple(allowed), "high")
    decision = resolve_passthrough_effort(requested, None, spec, enabled=True)
    assert (decision.value, decision.apply, decision.clamped_from) == (
        value,
        True,
        requested,
    )


def test_passthrough_keeps_supported_effort_and_applies_alias() -> None:
    assert not resolve_passthrough_effort("medium", None, SPEC, enabled=True).apply
    alias = resolve_passthrough_effort(None, "high", SPEC, enabled=True)
    assert (alias.value, alias.apply, alias.clamped_from) == ("high", True, None)
    assert resolve_passthrough_effort(None, "max", SPEC, enabled=True).value == "high"


def test_passthrough_normalizes_padded_supported_effort() -> None:
    padded = resolve_passthrough_effort(" high ", None, SPEC, enabled=True)
    assert (padded.value, padded.apply, padded.clamped_from) == ("high", True, None)


def test_passthrough_legacy_when_flag_off_or_no_catalog_efforts() -> None:
    assert not resolve_passthrough_effort("off", None, SPEC, enabled=False).apply
    legacy_alias = resolve_passthrough_effort(None, "high", SPEC, enabled=False)
    assert (legacy_alias.value, legacy_alias.apply) == ("high", True)
    no_efforts = ModelEffortSpec()
    assert not resolve_passthrough_effort("off", None, no_efforts, enabled=True).apply


def _widen_terra_efforts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Каталог `gpt-6.1-terra` с efforts [low, medium, high] и сброс кэша спек effort."""
    terra = server.FLEET["models"]["gpt-6.1-terra"]
    monkeypatch.setitem(terra, "efforts", ["low", "medium", "high"])
    monkeypatch.setattr(server, "_EFFORT_SPECS_CACHE", (None, {}))  # кэш не утекает между тестами


def _sent_request(handler: Any) -> dict[str, Any]:
    return dict(handler._serve_passthrough.call_args.args[2])


def test_route_clamps_effort_only_with_flag(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _widen_terra_efforts(monkeypatch)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.delenv("BRIDGE_EFFORT_CATALOG_ENABLED", raising=False)
    handler, _ = route({"model": "gpt-6.1-terra", "reasoning_effort": "off"})
    assert _sent_request(handler)["reasoning_effort"] == "off"  # прежнее поведение: дословно
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    handler, _ = route({"model": "gpt-6.1-terra", "reasoning_effort": "off"})
    assert _sent_request(handler)["reasoning_effort"] == "low"  # efforts [low, medium, high]: минимум
    handler, _ = route({"model": "gpt-6.1-terra"})
    assert "reasoning_effort" not in _sent_request(handler)  # без effort — прозрачно


# ---- /v1/models ------------------------------------------------------------------------


def test_effort_spec_mirrors_catalog_entry() -> None:
    entry = {"efforts": LMH, "default_effort": "low"}
    assert ModelEffortSpec.from_catalog_entry(entry) == ModelEffortSpec(
        tuple(LMH), "low"
    )
    empty = ModelEffortSpec()
    assert (
        ModelEffortSpec.from_catalog_entry({"efforts": [], "default_effort": None})
        == empty
    )
    assert ModelEffortSpec.from_catalog_entry(None) == empty
    assert ModelEffortSpec.from_catalog_entry(["efforts"]) == empty


def test_effort_spec_pinned_to_alias_effort_clamps_to_catalog() -> None:
    assert SPEC.pinned_to("low") == ModelEffortSpec(("low",), "low")
    assert SPEC.pinned_to("max") == ModelEffortSpec(("high",), "high")
    assert ModelEffortSpec().pinned_to("low") == ModelEffortSpec(("low",), "low")


def test_models_list_reports_catalog_efforts(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    monkeypatch.setattr(server, "_EFFORT_SPECS_CACHE", (None, {}))
    cards = {card["id"]: card for card in server._build_models_list()}
    checked = 0
    for mid, entry in server.FLEET["models"].items():
        if mid in cards:
            checked += 1
            assert cards[mid]["supported_reasoning_efforts"] == list(entry["efforts"])
            assert cards[mid]["default_reasoning_effort"] == entry["default_effort"]
    assert checked and cards["muse-spark-1.3"]["supported_reasoning_efforts"] == ["max"]


# ---- карантинный гейт: инварианты ------------------------------------------------------


def test_default_open_roles_are_unchanged() -> None:
    assert qg.DEFAULT_OPEN_ROLES == frozenset({"worker", "explorer", "probe"})
    assert "smoke" not in qg.DEFAULT_OPEN_ROLES
    assert qg.RoleClasses().class_of("smoke") == qg.CLASS_GATED


@pytest.mark.parametrize(
    "subagent_id,role",
    [
        ("probe-abc12345", "probe"),
        ("coder-abc-def", "coder"),
        ("Worker-1-2-3", "worker"),
        ("-weird", "adhoc"),
        (None, "adhoc"),
    ],
)
def test_role_from_subagent_id_handles_dashed_ids(subagent_id: Any, role: str) -> None:
    assert qg.role_from_subagent_id(subagent_id) == role
    assert (
        qg.role_from_subagent_id("", strict_anonymous=True) == qg.ROLE_ANONYMOUS_GATED
    )


def test_alias_card_pins_alias_effort(
    route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _widen_terra_efforts(monkeypatch)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    aliases = ("gpt-6.1-terra-low", "gpt-6.1-terra-max")
    monkeypatch.setattr(server, "ADVERTISED_EFFORT_ALIASES", aliases)
    cards = {card["id"]: card for card in server._build_models_list()}
    low, over = cards["gpt-6.1-terra-low"], cards["gpt-6.1-terra-max"]
    assert (low["supported_reasoning_efforts"], low["default_reasoning_effort"]) == (
        ["low"],
        "low",
    )
    # `max` вне каталога [low, medium, high]: алиас реально применит `high`, карточка не обещает лишнего.
    assert (over["supported_reasoning_efforts"], over["default_reasoning_effort"]) == (
        ["high"],
        "high",
    )


# ---- журнал клампа: значение effort приходит от клиента ---------------------------------


def test_sanitize_effort_for_log_strips_controls_and_truncates() -> None:
    dirty = "hi\r\nx\ty\x00" + "a" * 100
    clean = sanitize_effort_for_log(dirty)
    assert clean == "hixy" + "a" * 28 and clean.isprintable()
    assert sanitize_effort_for_log(dirty, 3) == "hix"
    assert "\n" not in sanitize_effort_for_log(["a\nb"])


def test_describe_clamp_has_no_line_breaks() -> None:
    line = describe_clamp("reasoning_effort", "off\n2099 FORGED", "high\r", "m")
    assert line == "clamp reasoning_effort 'off2099 FORGED' -> 'high' for model m"


def test_route_clamp_log_cannot_be_forged(
    route: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _widen_terra_efforts(monkeypatch)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_EFFORT_CATALOG_ENABLED", "1")
    forged = "bogus\r\n2099-01-01T00:00:00Z FORGED " + "x" * 500
    route({"model": "gpt-6.1-terra", "reasoning_effort": forged})
    lines = capsys.readouterr().err.splitlines()
    clamp_lines = [line for line in lines if "clamp passthrough" in line]
    assert len(clamp_lines) == 1 and len(clamp_lines[0]) < 200
    assert not any(line.startswith("2099-01-01") for line in lines)


def test_log_effort_max_chars_is_bounded_env_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N-01: журнальный лимит effort — дефолт 32 (константа модуля) и 42 из env; нечисло/<=0 -> дефолт."""
    monkeypatch.delenv("BRIDGE_LOG_EFFORT_MAX_CHARS", raising=False)
    assert server._LOG_EFFORT_MAX == DEFAULT_LOG_EFFORT_MAX_CHARS == 32
    monkeypatch.setenv("BRIDGE_LOG_EFFORT_MAX_CHARS", "42")
    assert server._env_limit("BRIDGE_LOG_EFFORT_MAX_CHARS", 32) == 42
    for bad in ("abc", "-5", "0"):
        monkeypatch.setenv("BRIDGE_LOG_EFFORT_MAX_CHARS", bad)
        assert server._env_limit("BRIDGE_LOG_EFFORT_MAX_CHARS", 32) == 32
