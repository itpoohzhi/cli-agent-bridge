"""build_catalog(mode="isolate"): дефект одной записи не ломает каталог (AC (а), спека §4.4.3)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Literal

import pytest

from adapters import ADAPTER_KINDS
from core.backend_adapter import FleetViolation, build_catalog

FLEET_FILE = Path(__file__).resolve().parents[1] / "fleet.json"


def raw_fleet() -> Dict[str, Any]:
    return copy.deepcopy(json.loads(FLEET_FILE.read_text(encoding="utf-8")))


def build(data: Dict[str, Any], mode: Literal["strict", "isolate"] = "isolate", **kwargs: Any) -> Dict[str, Any]:
    return build_catalog(data, ADAPTER_KINDS, mode=mode, **kwargs)


def model(data: Dict[str, Any], mid: str) -> Dict[str, Any]:
    return next(m for m in data["models"] if m["id"] == mid)


def test_strict_result_has_empty_rejected_key() -> None:
    catalog = build(raw_fleet(), "strict")
    assert catalog["rejected"] == {}


def test_isolate_on_clean_fleet_equals_strict() -> None:
    strict, isolate = build(raw_fleet(), "strict"), build(raw_fleet(), "isolate")
    assert strict == isolate


def test_one_broken_model_isolated_n_minus_1() -> None:
    data = raw_fleet()
    model(data, "gpt-6.1-terra")["efforts"] = ["turbo"]
    total = len(build(raw_fleet(), "strict")["models"])
    isolated = build(data, "isolate")
    assert len(isolated["models"]) == total - 1
    assert isolated["rejected"] == {"gpt-6.1-terra": "efforts_invalid"}
    assert "gpt-6.1-terra" not in isolated["order"]
    with pytest.raises(FleetViolation) as exc:
        build(data, "strict")
    assert exc.value.reason == "efforts_invalid"
    assert exc.value.model == "gpt-6.1-terra"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda m: m.update(efforts=[]), "efforts_invalid"),
        (lambda m: m.update(default_effort="max-plus"), "default_effort_invalid"),
        (lambda m: m.update(unexpected=1), "model_key_unknown"),
        (lambda m: m.update(backend="nope"), "model_backend_unknown"),
        (lambda m: m["images"].update(status="bogus"), "status_invalid"),
        (lambda m: m.update(input="text"), "status_inconsistent"),
        (lambda m: m.update(context_window="abc"), "context_window_invalid"),
        (
            lambda m: m["images"].update(status="probe", method="workspace-read"),
            "status_inconsistent",
        ),
    ],
)
def test_model_defect_classes_rejected_in_isolate(mutation: Any, reason: str) -> None:
    data = raw_fleet()
    mutation(model(data, "gemini-4-argon"))
    assert build(data, "isolate")["rejected"] == {"gemini-4-argon": reason}
    with pytest.raises(FleetViolation) as exc:
        build(data, "strict")
    assert exc.value.reason == reason


def test_non_dict_model_item_is_rejected_by_index() -> None:
    data = raw_fleet()
    data["models"].append("garbage")
    isolated = build(data, "isolate")
    assert isolated["rejected"] == {f"#{len(data['models']) - 1}": "model_invalid"}
    with pytest.raises(FleetViolation):
        build(data, "strict")


def test_broken_non_required_backend_rejects_its_models() -> None:
    data = raw_fleet()
    data["default_model"] = "gemini-4-argon"
    data["backends"]["muse"]["max_concurrent"] = 2
    isolated = build(data, "isolate")
    muse_models = {m["id"] for m in data["models"] if m["backend"] == "muse"}
    assert set(isolated["rejected"]) == muse_models
    assert set(isolated["rejected"].values()) == {"backend_muse_max_concurrent_invalid"}
    assert "muse" not in isolated["backends"]
    assert not muse_models & set(isolated["models"])
    with pytest.raises(FleetViolation) as exc:
        build(data, "strict")
    assert exc.value.reason == "backend_muse_max_concurrent_invalid"


def test_broken_required_backend_is_fatal_even_in_isolate() -> None:
    data = raw_fleet()
    data["backends"]["agy"]["required"] = True
    data["backends"]["agy"]["base_url"] = "http://example.com/v1"
    with pytest.raises(FleetViolation) as exc:
        build(data, "isolate")
    assert exc.value.reason == "backend_base_url_invalid"


def test_default_model_rejected_is_fatal_no_substitution() -> None:
    data = raw_fleet()
    model(data, data["default_model"])["efforts"] = []
    with pytest.raises(FleetViolation) as exc:
        build(data, "isolate")
    assert exc.value.reason == "default_model_invalid"


def test_env_model_invalid_is_fatal_in_isolate() -> None:
    with pytest.raises(FleetViolation) as exc:
        build(raw_fleet(), "isolate", env_model="no-such-model")
    assert exc.value.reason == "env_model_invalid"


def test_duplicate_id_keeps_first_in_isolate() -> None:
    data = raw_fleet()
    duplicate = copy.deepcopy(model(data, "gemini-4-argon"))
    duplicate["name"] = "second"
    data["models"].append(duplicate)
    isolated = build(data, "isolate")
    assert isolated["rejected"] == {"gemini-4-argon": "duplicate_id"}
    assert isolated["models"]["gemini-4-argon"]["name"] != "second"
    with pytest.raises(FleetViolation) as exc:
        build(data, "strict")
    assert exc.value.reason == "duplicate_id"


def test_all_backends_broken_is_fatal() -> None:
    data = raw_fleet()
    for entry in data["backends"].values():
        entry["max_concurrent"] = 0
    with pytest.raises(FleetViolation) as exc:
        build(data, "isolate")
    assert exc.value.reason == "backends_none_enabled"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda d: d.update(schema_version=9), "schema_version_invalid"),
        (lambda d: d.update(bogus=1), "fleet_key_unknown"),
        (lambda d: d.update(backends={}), "backends_invalid"),
        (lambda d: d.update(image_limits=None), "limits_invalid"),
        (lambda d: d["image_limits"].update(max_images=0), "limits_invalid"),
        (lambda d: d.update(admission=[]), "admission_invalid"),
        (lambda d: d.update(models=[]), "models_invalid"),
        (lambda d: d.update(default_model="missing"), "default_model_invalid"),
    ],
)
def test_global_class_one_defects_fatal_in_both_modes(
    mutation: Any, reason: str
) -> None:
    for mode in ("strict", "isolate"):
        data = raw_fleet()
        mutation(data)
        with pytest.raises(FleetViolation) as exc:
            build(data, mode)
        assert exc.value.reason == reason


def test_not_a_dict_is_fatal_in_isolate() -> None:
    invalid: Any = []
    with pytest.raises(FleetViolation) as exc:
        build(invalid, "isolate")
    assert exc.value.reason == "fleet_unreadable"


def test_models_of_disabled_backend_are_skipped_not_rejected() -> None:
    data = raw_fleet()
    data["backends"]["droid"]["enabled"] = (
        False  # droid первичен для deepseek в боевом каталоге
    )
    catalog = build(data, "isolate")
    assert "deepseek-v4.1-flash" not in catalog["models"]
    assert "deepseek-v4.1-flash" not in catalog["rejected"]
