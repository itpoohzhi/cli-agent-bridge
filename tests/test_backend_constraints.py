"""KindConstraints: паритет legacy ↔ constraints и allowlist базовых URL (спека §3.5)."""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from typing import Any, Dict

import pytest

import core.backend_adapter as backend_adapter
from adapters import ADAPTER_KINDS
from core.backend_adapter import (
    AllowEntry,
    KindConstraints,
    backend_entry_error,
    build_catalog,
    kind_constraints,
)

FLEET = json.loads(
    (Path(__file__).resolve().parents[1] / "fleet.json").read_text(encoding="utf-8")
)


def error(entry: Dict[str, Any], *, constraints: bool, **kwargs: Any) -> str:
    return backend_entry_error(
        "x", entry, ADAPTER_KINDS, constraints_enabled=constraints, **kwargs
    )


@pytest.mark.parametrize("backend_id", sorted(FLEET["backends"]))
def test_parity_on_current_fleet(backend_id: str) -> None:
    entry = FLEET["backends"][backend_id]
    assert error(entry, constraints=False) == error(entry, constraints=True) == ""


def test_adapters_declare_constraints() -> None:
    assert kind_constraints(ADAPTER_KINDS, "muse") == KindConstraints(
        max_concurrent_max=None,
        pin_required=True,
        options_schema={"streaming_mode": ("exec", "serve")},
    )
    assert kind_constraints(ADAPTER_KINDS, "passthrough").base_url_allowed
    assert kind_constraints(ADAPTER_KINDS, "droid") == KindConstraints()


@pytest.mark.parametrize("max_concurrent", (2, 32))
def test_muse_max_concurrent_above_one_accepted(max_concurrent: int) -> None:
    entry = copy.deepcopy(FLEET["backends"]["muse"])
    entry["max_concurrent"] = max_concurrent
    assert error(entry, constraints=False) == ""
    assert error(entry, constraints=True) == ""


def test_muse_without_pin_rejected_in_both_branches() -> None:
    entry = copy.deepcopy(FLEET["backends"]["muse"])
    entry.pop("technical_ref")
    assert error(entry, constraints=False) == error(entry, constraints=True)
    assert error(entry, constraints=True) == "backend_technical_ref_missing"


def test_options_on_passthrough_rejected_in_both_branches() -> None:
    entry = copy.deepcopy(FLEET["backends"]["agy"])
    entry["options"] = {"streaming_mode": "exec"}
    assert (
        error(entry, constraints=False)
        == error(entry, constraints=True)
        == "backend_options_invalid"
    )


def test_bad_streaming_mode_same_slug() -> None:
    entry = copy.deepcopy(FLEET["backends"]["muse"])
    entry["options"] = {"streaming_mode": "warp"}
    assert error(entry, constraints=False) == error(entry, constraints=True)
    assert error(entry, constraints=True) == "backend_streaming_mode_invalid"


def test_base_url_unexpected_for_kinds_without_http() -> None:
    entry = copy.deepcopy(FLEET["backends"]["muse"])
    entry["base_url"] = "http://127.0.0.1:1/v1"
    assert error(entry, constraints=False) == error(entry, constraints=True)
    assert error(entry, constraints=True) == "backend_base_url_unexpected"


def test_api_key_rejected_for_kind_without_key_support() -> None:
    entry = copy.deepcopy(FLEET["backends"]["muse"])
    entry["api_key_env"] = "X_KEY"
    assert (
        error(entry, constraints=False)
        == error(entry, constraints=True)
        == "backend_key_unknown"
    )


def test_base_url_outside_allowlist_rejected() -> None:
    entry = copy.deepcopy(FLEET["backends"]["agy"])
    allow = {"x": (AllowEntry("http", "127.0.0.1", 9999, "/v1"),)}
    assert error(entry, constraints=True, allowlist=allow) == "backend_base_url_invalid"
    allow = {"x": (AllowEntry("http", "127.0.0.1", 9887, "/v1"),)}
    assert error(entry, constraints=True, allowlist=allow) == ""


def test_default_policy_is_loopback_only() -> None:
    entry = copy.deepcopy(FLEET["backends"]["agy"])
    entry["base_url"] = "http://10.0.0.5:9887/v1"
    assert error(entry, constraints=True) == "backend_base_url_invalid"
    entry["base_url"] = "http://127.0.0.1:99999/v1"
    assert error(entry, constraints=True) == "backend_base_url_invalid"


def test_default_policy_overridable_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = copy.deepcopy(FLEET["backends"]["agy"])
    entry["base_url"] = "http://127.0.0.1:9887/api"
    assert error(entry, constraints=True) == "backend_base_url_invalid"
    monkeypatch.setenv(
        "BRIDGE_DEFAULT_BASE_URL_POLICY", r"http://127\.0\.0\.1:([0-9]{1,5})/api"
    )
    assert error(entry, constraints=True) == ""


def test_allow_entry_matches_boundaries() -> None:
    entry = AllowEntry("http", "127.0.0.1", 10830, "/go")
    assert entry.matches("http://127.0.0.1:10830/go/v1")
    assert entry.matches("http://127.0.0.1:10830/go")
    assert not entry.matches("http://127.0.0.1:10830/gone")
    assert not entry.matches("https://127.0.0.1:10830/go")
    assert not entry.matches("http://127.0.0.1:10831/go")
    assert not entry.matches("http://user@127.0.0.1:10830/go")


def test_catalog_builds_identically_with_constraints_enabled() -> None:
    legacy = build_catalog(copy.deepcopy(FLEET), ADAPTER_KINDS)
    modern = build_catalog(
        copy.deepcopy(FLEET), ADAPTER_KINDS, constraints_enabled=True
    )
    assert legacy == modern


def test_new_branch_has_no_vendor_literals() -> None:
    """В ветке `constraints is not None` нет литералов имён видов (AST-оракул)."""
    kinds = set(ADAPTER_KINDS)
    source = inspect.getsource(backend_adapter.backend_entry_error)
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "constraints is not None" in ast.unparse(
            node.test
        ):
            for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(sub, ast.Constant) and sub.value in kinds:
                    offenders.append(sub.value)
    assert offenders == []
