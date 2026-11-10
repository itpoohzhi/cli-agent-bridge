from __future__ import annotations

# Прямые детерминированные проверки core/effort_policy.py: границы шкалы, дефолты, неизменяемость.

import sys
from collections.abc import Iterator, Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import effort_policy as policy  # noqa: E402
from core.effort_policy import (  # noqa: E402
    EFFORT_LEVELS,
    EFFORT_ORDER,
    FLAG_EFFORT_CATALOG,
    EffortResolution,
    ModelEffortCardFields,
    ModelEffortSpec,
    clamp_effort_downward,
    resolve_alias_effort,
    resolve_passthrough_effort,
)

LMH = ("low", "medium", "high")


@pytest.mark.parametrize(
    "candidate,allowed,default,expected",
    [
        ("HIGH", ["low", "high"], "x", ("high", False)),
        ("high", ["High"], "x", ("High", False)),
        ("bogus", ["bogus"], "x", ("bogus", False)),
        ("off", LMH, "x", ("low", True)),
        ("off", ["high"], "low", ("high", True)),
        ("medium", ["low", "high"], "x", ("low", True)),
        ("xhigh", LMH, "x", ("high", True)),
        ("bogus", LMH, "dflt", ("dflt", True)),
        ("high", [], "dflt", ("dflt", True)),
        ("high", ["bogus"], "dflt", ("dflt", True)),
        ("xhigh", ["bogus", "low"], "x", ("low", True)),
        ("high", ["Low", "low"], "x", ("Low", True)),
    ],
)
def test_clamp_effort_downward_boundaries(
    candidate: str, allowed: list[str], default: str, expected: tuple[str, bool]
) -> None:
    assert clamp_effort_downward(candidate, allowed, default) == expected


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"efforts": ["low"], "default_effort": 5}, ModelEffortSpec(("low",), None)),
        ({"efforts": ["low"], "default_effort": ""}, ModelEffortSpec(("low",), None)),
        (
            {"efforts": ("low", "high"), "default_effort": "high"},
            ModelEffortSpec(("low", "high"), "high"),
        ),
        ({"efforts": "low"}, ModelEffortSpec()),
        ({"efforts": [1, None, "low"]}, ModelEffortSpec(("low",))),
        ({"efforts": ["bogus", "unknown"]}, ModelEffortSpec()),
        (
            {"efforts": [" High ", "high", "LOW", "off"], "default_effort": " HIGH "},
            ModelEffortSpec(("off", "low", "high"), "high"),
        ),
        ({}, ModelEffortSpec()),
    ],
)
def test_effort_spec_from_catalog_entry_fields(
    entry: Any, expected: ModelEffortSpec
) -> None:
    assert ModelEffortSpec.from_catalog_entry(entry) == expected


def test_from_catalog_entry_normalizes_order_and_default() -> None:
    entry = {"efforts": ["high", "low", "high", "max"], "default_effort": "high"}
    assert ModelEffortSpec.from_catalog_entry(entry) == ModelEffortSpec(
        ("low", "high", "max"), "high"
    )
    outside = {"efforts": ["low", "high"], "default_effort": "max"}
    assert ModelEffortSpec.from_catalog_entry(outside) == ModelEffortSpec(
        ("low", "high"), None
    )


def test_pinned_to_unknown_effort_falls_back_to_lowest_allowed() -> None:
    assert ModelEffortSpec(("low", "high"), "high").pinned_to(
        "bogus"
    ) == ModelEffortSpec(("high",), "high")
    assert ModelEffortSpec(("low", "high")).pinned_to("bogus") == ModelEffortSpec(
        ("low",), "low"
    )
    assert ModelEffortSpec().pinned_to("bogus") == ModelEffortSpec(("bogus",), "bogus")


def test_effort_scale_and_catalog_flag_are_single_source() -> None:
    assert policy.EFFORT_LEVELS == EFFORT_LEVELS == (
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    )
    assert EFFORT_ORDER == ("off", *EFFORT_LEVELS, "ultra")
    assert FLAG_EFFORT_CATALOG == "BRIDGE_EFFORT_CATALOG_ENABLED"


def test_passthrough_empty_spec_never_indexes_efforts() -> None:
    assert resolve_passthrough_effort("bogus", None, ModelEffortSpec(), enabled=True) == EffortResolution()


@pytest.mark.parametrize("default,expected", [(None, "low"), ("medium", "medium")])
def test_passthrough_unknown_effort_uses_default_or_lowest(
    default: str | None, expected: str
) -> None:
    decision = resolve_passthrough_effort(
        "bogus", None, ModelEffortSpec(LMH, default), enabled=True
    )
    assert decision == EffortResolution(expected, True, "bogus")


def test_passthrough_ignores_absent_effort() -> None:
    spec = ModelEffortSpec(LMH, "high")
    for alias in ("  ", None):
        assert (
            resolve_passthrough_effort(None, alias, spec, enabled=True)
            == EffortResolution()
        )
    assert resolve_passthrough_effort(
        None, " low ", spec, enabled=False
    ) == EffortResolution("low", True)


@pytest.mark.parametrize("requested", ["", "   ", 123])
def test_passthrough_clamps_blank_or_non_string_explicit_effort(requested: object) -> None:
    spec = ModelEffortSpec(LMH, "medium")
    assert resolve_passthrough_effort(requested, None, spec, enabled=True) == EffortResolution(
        "medium", True, str(requested)
    )
    assert resolve_passthrough_effort(requested, None, ModelEffortSpec(LMH), enabled=True) == EffortResolution(
        "low", True, str(requested)
    )
    assert resolve_passthrough_effort(requested, None, spec, enabled=False) == EffortResolution()


def test_passthrough_non_string_effort_with_alias_pins_alias_level() -> None:
    spec = ModelEffortSpec(LMH, "high")
    assert resolve_passthrough_effort(5, "high", spec, enabled=True) == EffortResolution(
        "high", True, "5"
    )


def test_passthrough_pins_alias_before_clamping_explicit_effort() -> None:
    pinned = resolve_passthrough_effort("high", "low", ModelEffortSpec(LMH, "high"), enabled=True)
    assert (pinned.value, pinned.apply, pinned.clamped_from) == ("low", True, "high")


def test_effort_resolution_defaults_are_transparent() -> None:
    assert (
        EffortResolution().value,
        EffortResolution().apply,
        EffortResolution().clamped_from,
    ) == (None, False, None)


@pytest.mark.parametrize(
    "obj,field",
    [
        (ModelEffortSpec(), "default"),
        (EffortResolution(), "value"),
        (ModelEffortCardFields("high", LMH), "default_effort"),
    ],
)
def test_policy_dataclasses_are_frozen_and_slotted(obj: Any, field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(obj, field, "x")
    assert not hasattr(obj, "__dict__")


def test_effort_scale_ranks_follow_order() -> None:
    assert [policy._RANK[name] for name in policy.EFFORT_ORDER] == list(
        range(len(policy.EFFORT_ORDER))
    )


@pytest.mark.parametrize(
    "candidate,allowed,expected",
    [
        ("bogus", ["low", "high"], ("high", True)),
        ("bogus", ["weird"], ("high", True)),
        ("medium", ["weird"], ("high", True)),
        ("off", ["low", "high"], ("low", True)),
        ("ultra", ["low", "high"], ("high", True)),
        ("HIGH", ["low", "High"], ("High", False)),
    ],
)
def test_clamp_unknown_scale_or_unranked_allowed_uses_default(
    candidate: str, allowed: list[str], expected: tuple[str, bool]
) -> None:
    assert policy.clamp_effort_downward(candidate, allowed, "high") == expected


CAT = {"m": {}, "other": {}}


@pytest.mark.parametrize(
    "raw,enabled,expected",
    [
        ("m-high", True, ("m", "high")),
        ("other-low", True, ("other", "low")),
        ("m-high", False, None),
        ("m", True, None),
        ("m-bogus", True, None),
        ("zzz-high", True, None),
        ("high", True, None),
    ],
)
def test_resolve_alias_effort_boundaries(raw: str, enabled: bool, expected: tuple[str, str] | None) -> None:
    assert resolve_alias_effort(raw, CAT, ("low", "high"), enabled) == expected


def test_from_catalog_entry_rejects_default_outside_unranked_efforts() -> None:
    entry = {"efforts": ["vendor", "low"], "default_effort": "max"}
    assert ModelEffortSpec.from_catalog_entry(entry).default is None
    entry = {"efforts": ["vendor", "low"], "default_effort": "vendor"}
    assert ModelEffortSpec.from_catalog_entry(entry) == ModelEffortSpec(("low",), None)


def test_passthrough_canonicalizes_case_and_pins_stripped_alias() -> None:
    spec = ModelEffortSpec(("high",), "high")
    assert resolve_passthrough_effort("HIGH", None, spec, enabled=True) == EffortResolution("high", True)
    assert resolve_passthrough_effort("high", None, spec, enabled=True) == EffortResolution()
    pinned = resolve_passthrough_effort(None, " low ", ModelEffortSpec(LMH, "high"), enabled=True)
    assert (pinned.value, pinned.clamped_from) == ("low", None)


class _CountingCatalogue(Mapping[str, object]):
    """Каталог на 1001 ключ со счётчиками обходов и обращений."""

    def __init__(self) -> None:
        self.data: Mapping[str, object] = {f"k{i}": {} for i in range(1000)} | {"m": {}}
        self.iterations = 0
        self.lookups = 0

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, key: str) -> object:
        self.lookups += 1
        return self.data[key]

    def __contains__(self, key: object) -> bool:
        self.lookups += 1
        return key in self.data


def test_resolve_alias_effort_does_not_scan_catalogue() -> None:
    catalogue = _CountingCatalogue()
    assert len(catalogue) == 1001
    assert resolve_alias_effort("m-high", catalogue, ("high",), False) is None
    assert (catalogue.iterations, catalogue.lookups) == (0, 0)
    assert resolve_alias_effort("m-high", catalogue, ("high",), True) == ("m", "high")
    assert catalogue.iterations == 0


def test_resolve_alias_effort_exact_catalogue_entry_wins() -> None:
    assert resolve_alias_effort("m-high", {"m": {}, "m-high": {}}, ("high",), True) is None
